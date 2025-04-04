from __future__ import annotations

import re
import os.path
import importlib
import importlib.util
import inspect
import logging
import sys
from types import ModuleType
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
    cast,
)

import sqlalchemy
from sqlalchemy import Column, Integer, String, Text, select
from sqlalchemy.engine import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from sopel import config, loader, plugins
from sopel.config import types
from sopel.lifecycle import deprecated

if sys.version_info.major >= 3 and sys.version_info.minor >= 7:
    from importlib import resources
else:
    import importlib_resources as resources

LOGGER = logging.getLogger(__name__)

MODULE_JOBS = []
"""Jobs registered by modules.

Each job is a dictionary with ``interval`` and ``function`` keys.
See :func:`sopel.modules.jobs.interval`.
"""

# Declare the module base
Base = declarative_base()


class ModuleSection(config.types.StaticSection):
    """Configuration section for a module."""
    # TODO: there are plans to reform this class to be more useful
    # and to have proper implementations for common use cases
    # such as storage access, API keys, and more.
    pass


class ExampleSection(config.types.StaticSection):
    """Configuration section for the example plugin."""
    # this class is used to validate the example plugin's configuration
    # from examples/custom_plugin.py
    foo = config.types.ValidatedAttribute('foo', str)
    bar = config.types.ValidatedAttribute('bar', config.types.boolean, default=False)


class PersistentPluginSection(config.types.StaticSection):
    """Configuration section for a persistent plugin."""
    # This class is used to validate the configuration for a persistent plugin.
    # It is used in the tests.
    foo = config.types.ValidatedAttribute('foo', str)
    bar = config.types.ValidatedAttribute('bar', config.types.boolean, default=False)


class Nickname(Base):
    """Model for a nickname in the plugin's database."""
    __tablename__ = 'nicknames'

    id = Column(Integer, primary_key=True)
    """Primary key for the nickname."""
    name = Column(String(255), nullable=False)
    """Nickname's name."""
    data = Column(Text)
    """Nickname's data."""


class SopelDB:
    """Interface to a SQLite database for a plugin.

    Plugins can use this object to store and retrieve data in a SQLite database
    created specifically for the given plugin.

    :param plugin: the plugin's name
    :type plugin: str
    :param filename: the filename for the SQLite database
    :type filename: str
    """
    def __init__(self, plugin, filename):
        self.filename = filename
        self.plugin = plugin
        # Ensure the folder exists
        folder_path = os.path.dirname(filename)
        if not os.path.isdir(folder_path):
            os.makedirs(folder_path)

        # Create the database engine and session
        self.engine = create_engine('sqlite:///%s' % filename, future=True)
        self.ssession = sessionmaker(bind=self.engine, future=True)
        Base.metadata.create_all(self.engine)

    def get_nick_id(self, nickname, create=True):
        """Return the ID of a nickname.

        :param str nickname: the nickname to look up
        :param bool create: whether to create the nickname if it doesn't exist
        :return: the ID of the nickname
        :rtype: int
        """
        nickname = nickname.lower()
        session = self.ssession()

        try:
            result = session.execute(
                select(Nickname).where(Nickname.name == nickname)
            ).scalar_one_or_none()

            if result is None:
                if not create:
                    raise ValueError('No ID exists for the nickname %s' % nickname)
                result = Nickname(name=nickname)
                session.add(result)
                session.commit()

            return result.id
        finally:
            session.close()

    def get_nick_value(self, nickname, key):
        """Retrieve data stored for a given nickname.

        :param str nickname: the nickname to look up data for
        :param str key: the key to look up
        :return: the data stored for the given key and nickname
        :rtype: str
        """
        nickname = nickname.lower()
        session = self.ssession()

        try:
            result = session.execute(
                select(Nickname).where(Nickname.name == nickname)
            ).scalar_one_or_none()

            if result is not None:
                data = result.data
                if data:
                    data = eval(data)
                    return data.get(key)
        finally:
            session.close()

        return None

    def set_nick_value(self, nickname, key, value):
        """Set a value for a given nickname and key.

        :param str nickname: the nickname to associate the data with
        :param str key: the key to store the data under
        :param value: the data to store
        """
        nickname = nickname.lower()
        session = self.ssession()

        try:
            nick = session.execute(
                select(Nickname).where(Nickname.name == nickname)
            ).scalar_one_or_none()

            if nick is None:
                nick = Nickname(name=nickname)
                session.add(nick)
                data = {}
            else:
                data = nick.data or '{}'
                data = eval(data)

            data[key] = value
            nick.data = str(data)
            session.commit()
        finally:
            session.close()

    def delete_nick_value(self, nickname, key):
        """Remove a value for a given nickname and key.

        :param str nickname: the nickname to remove the data from
        :param str key: the key to remove
        """
        nickname = nickname.lower()
        session = self.ssession()

        try:
            nick = session.execute(
                select(Nickname).where(Nickname.name == nickname)
            ).scalar_one_or_none()

            if nick is not None:
                data = nick.data or '{}'
                data = eval(data)
                if key in data:
                    del data[key]
                    nick.data = str(data)
                    session.commit()
        finally:
            session.close()

    def delete_nick_group(self, nickname):
        """Remove all values for a given nickname.

        :param str nickname: the nickname to remove all data for
        """
        nickname = nickname.lower()
        session = self.ssession()

        try:
            nick = session.execute(
                select(Nickname).where(Nickname.name == nickname)
            ).scalar_one_or_none()

            if nick is not None:
                session.delete(nick)
                session.commit()
        finally:
            session.close()

    def merge_nick_groups(self, nick1, nick2):
        """Merge two nickname groups.

        Takes all the key-value pairs in the group belonging to nick2, and
        adds them to nick1. Then deletes nick2's group.

        :param str nick1: the nickname to merge data into
        :param str nick2: the nickname to merge data from
        """
        nick1 = nick1.lower()
        nick2 = nick2.lower()
        session = self.ssession()

        try:
            nick1_id = self.get_nick_id(nick1)
            nick2_id = self.get_nick_id(nick2)

            if nick1_id == nick2_id:
                return

            nick1_obj = session.execute(
                select(Nickname).where(Nickname.id == nick1_id)
            ).scalar_one()
            nick2_obj = session.execute(
                select(Nickname).where(Nickname.id == nick2_id)
            ).scalar_one()

            # Get nick1's data, nick2's data
            nick1_data = nick1_obj.data or '{}'
            nick1_data = eval(nick1_data)
            nick2_data = nick2_obj.data or '{}'
            nick2_data = eval(nick2_data)

            # Merge nick2's data into nick1
            for key, value in nick2_data.items():
                nick1_data[key] = value

            nick1_obj.data = str(nick1_data)
            session.delete(nick2_obj)
            session.commit()
        finally:
            session.close()

    def unalias_nick(self, alias):
        """Remove an alias.

        If ``alias`` is in a group, returns the group's preferred nick, else
        return ``alias``.

        :param str alias: the nick to remove as an alias
        :return: the preferred nick for the alias
        :rtype: str
        """
        alias = alias.lower()
        nick = self.get_nick_value(alias, 'nick')

        if nick is None:
            return alias

        self.delete_nick_group(alias)
        return nick

    def check_nick_valid(self, nick):
        """Check if a nick is valid for use as a nickname group.

        :param str nick: the nickname to check
        :return: True if the nickname is valid, False otherwise
        :rtype: bool
        """
        nick = nick.lower()
        if not nick:
            return False

        session = self.ssession()

        try:
            result = session.execute(
                select(Nickname).where(Nickname.name == nick)
            ).scalar_one_or_none()

            if result is not None:
                # Get the nick's data
                data = result.data or '{}'
                data = eval(data)
                if 'nick' in data:
                    return False
        finally:
            session.close()

        return True

    def alias_nick(self, nick, alias):
        """Create an alias for a nick.

        :param str nick: the nickname to create an alias for
        :param str alias: the alias to create
        :return: True if the alias was created, False otherwise
        :rtype: bool
        """
        nick = nick.lower()
        alias = alias.lower()

        if nick == alias:
            return False

        if not self.check_nick_valid(alias):
            return False

        self.set_nick_value(alias, 'nick', nick)
        return True

    def find_nick_from_aliases(self, alias):
        """Find the preferred nick for an alias.

        :param str alias: the alias to look up
        :return: the preferred nick for the alias
        :rtype: str
        """
        alias = alias.lower()
        session = self.ssession()

        try:
            result = session.execute(
                select(Nickname).where(Nickname.name == alias)
            ).scalar_one_or_none()

            if result is not None:
                data = result.data or '{}'
                data = eval(data)
                nick = data.get('nick')
                if nick:
                    return nick
        finally:
            session.close()

        return alias


class SettingsDict(dict):
    """A simple dict subclass for storing module settings.

    Used for sections where the keys are not known in advance.
    """
    def __setitem__(self, key, value):
        """Set a key-value pair in the dict.

        :param str key: the key to set
        :param value: the value to set
        """
        super().__setitem__(key.lower(), value)

    def __getitem__(self, key):
        """Get a value from the dict.

        :param str key: the key to look up
        :return: the value for the key
        """
        return super().__getitem__(key.lower())


def find_modules(config):
    """Find modules to load.

    :param config: Sopel's configuration
    :type config: :class:`sopel.config.Config`
    :return: a list of modules to load
    :rtype: list
    """
    modules = []

    # Get all the folders
    for path in config.core.extra:
        modules.extend(plugins.find_modules(path))

    # Get the core modules
    modules.extend(plugins.find_modules('sopel.modules'))

    return modules


def _load_module(path, name, is_enabled=True):
    """Load a module, and register its callables.

    :param str path: the path to the module
    :param str name: the name of the module
    :param bool is_enabled: whether the module is enabled
    :return: the loaded module
    :rtype: :class:`ModuleType`
    """
    plugin = plugins.load_module(path, name)

    if hasattr(plugin, 'configure'):
        plugin.configure.plugin_name = name

    return plugin


def setup(bot):
    """Set up the bot by loading modules and callables.

    :param bot: the bot to set up
    :type bot: :class:`sopel.bot.Sopel`
    """
    LOGGER.info('Setting up modules...')
    bot.callables = {}
    bot.shutdown_methods = []

    # Set defaults for config sections
    bot.config.define_section('core', config.core_section.CoreSection)
    bot.config.define_section('example', ExampleSection)
    bot.config.define_section('persistent_plugin', PersistentPluginSection)

    # Load modules
    usable_modules = plugins.get_usable_modules(bot.config)
    for name, info in usable_modules.items():
        # Load new modules
        path, is_enabled = info

        try:
            module = _load_module(path, name, is_enabled)
        except Exception as e:
            LOGGER.exception('Error loading %s: %s', name, e)
            continue

        if not is_enabled:
            continue

        # Handle setup
        if hasattr(module, 'setup'):
            try:
                module.setup(bot)
            except Exception as e:
                LOGGER.exception('Error in setup for %s: %s', name, e)
                continue

    LOGGER.info('Modules setup completed.')


def reload_module(bot, name):
    """Reload a module.

    :param bot: the bot to reload the module for
    :type bot: :class:`sopel.bot.Sopel`
    :param str name: the name of the module to reload
    :return: the reloaded module
    :rtype: :class:`ModuleType`
    """
    return plugins.reload_module(bot, name)