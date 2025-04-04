"""IRC Tools for ISUPPORT management.

When a server wants to advertise its features and settings, it can use the
``RPL_ISUPPORT`` command (``005`` numeric) with a list of arguments.

.. seealso::

    https://modern.ircdocs.horse/#rplisupport-005

"""
# Copyright 2019, Florian Strzelecki <florian.strzelecki@gmail.com>
#
# Licensed under the Eiffel Forum License 2.
from __future__ import annotations

from collections import OrderedDict
import functools
import itertools
import re
from typing import Dict


def _optional(parser, default=None):
    # set a parser as optional: will always return the default value provided
    # if there is no value (empty or None)
    @functools.wraps(parser)
    def wrapped(value):
        if not value:
            return default
        return parser(value)
    return wrapped


def _no_value(value):
    # always ignore the value
    return None


def _single_character(value):
    if len(value) > 1:
        raise ValueError('Too many characters: %r.' % value)

    return value


def _map_items(parser=str, map_separator=',', item_separator=':'):
    @functools.wraps(parser)
    def wrapped(value):
        items = sorted(
            item.split(item_separator)
            for item in value.split(map_separator))

        return tuple(
            (k, parser(v) if v else None)
            for k, v in items
        )
    return wrapped


def _parse_chanmodes(value):
    items = value.split(',')

    if len(items) < 4:
        raise ValueError('Not enough channel types to unpack from %r.' % value)

    # add extra channel mode types to their own tuple
    # result in (A, B, C, D, (E, F, G, H, ..., Z))
    # where A, B, C, D = result[:4]
    # and extras = result[4]
    return tuple(items[:4]) + (tuple(items[4:]),)


def _parse_elist(value):
    # letters are case-insensitives
    return tuple(sorted(set(letter.upper() for letter in value)))


def _parse_extban(value):
    args = value.split(',')

    if len(args) < 2:
        raise ValueError('Invalid value for EXTBAN: %r.' % value)

    prefix = args[0] or None
    items = tuple(sorted(set(args[1])))

    return (prefix, items)


def _parse_prefix(value):
    result = re.match(r'\((?P<modes>\S+)\)(?P<prefixes>\S+)', value)

    if not result:
        raise ValueError('Invalid value for PREFIX: %r' % value)

    modes = result.group('modes')
    prefixes = result.group('prefixes')

    if len(modes) != len(prefixes):
        raise ValueError('Mode list does not match for PREFIX: %r' % value)

    return tuple(zip(modes, prefixes))


ISUPPORT_PARSERS = {
    'AWAYLEN': int,
    'CASEMAPPING': str,
    'CHANLIMIT': _map_items(int),
    'CHANMODES': _parse_chanmodes,
    'CHANNELLEN': int,
    'CHANTYPES': _optional(tuple),
    'ELIST': _parse_elist,
    'EXCEPTS': _optional(_single_character, default='e'),
    'EXTBAN': _parse_extban,
    'HOSTLEN': int,
    'INVEX': _optional(_single_character, default='I'),
    'KICKLEN': int,
    'MAXLIST': _map_items(int),
    'MAXTARGETS': _optional(int),
    'MODES': _optional(int),
    'NETWORK': str,
    'NICKLEN': int,
    'PREFIX': _optional(_parse_prefix),
    'SAFELIST': _no_value,
    'SILENCE': _optional(int),
    'STATUSMSG': _optional(tuple),
    'TARGMAX': _optional(_map_items(int), default=tuple()),
    'TOPICLEN': int,
    'USERLEN': int,
}


def parse_parameter(arg):
    items = arg.split('=', 1)
    if len(items) == 2:
        key, value = items
    else:
        key, value = items[0], None

    if key.startswith('-'):
        # ignore value for removed parameters
        return (key, None)

    parser = ISUPPORT_PARSERS.get(key, _optional(str))
    return (key, parser(value))


class ISupport:
    """Storage class for IRC's ``ISUPPORT`` feature.

    An instance of ``ISupport`` can be used as a read-only dict, to store
    features advertised by the IRC server::

        >>> isupport = ISupport(chanlimit=(('&', None), ('#', 70)))
        >>> isupport['CHANLIMIT']
        (('&', None) ('#', 70))
        >>> isupport.CHANLIMIT  # some parameters are also properties
        {
            '&': None,
            '#': 70,
        }
        >>> 'chanlimit' in isupport  # case-insensitive
        True
        >>> 'chanmode' in isupport
        False
        >>> isupport.CHANMODE  # not advertised by the server!
        Traceback (most recent call last):
          File "<stdin>", line 1, in <module>
        AttributeError: 'ISupport' object has no attribute 'CHANMODE'

    The list of possible parameters can be found at
    `modern.ircdocs.horse's RPL_ISUPPORT Parameters`__.

    .. __: https://modern.ircdocs.horse/#rplisupport-parameters
    """
    def __init__(self, **kwargs):
        self.__isupport = dict(
            (key.upper(), value)
            for key, value in kwargs.items()
            if not key.startswith('-'))

    def __getitem__(self, key):
        key_ci = key.upper()
        if key_ci not in self.__isupport:
            raise KeyError(key_ci)
        return self.__isupport[key_ci]

    def __contains__(self, key):
        return key.upper() in self.__isupport

    def __getattr__(self, name):
        if name not in self.__isupport:
            raise AttributeError(name)

        return self.__isupport[name]

    def __setattr__(self, name, value):
        # make sure you can't set the value of any ISUPPORT attribute yourself
        if name == '_ISupport__isupport':
            # allow to set self.__isupport inside of the class
            super().__setattr__(name, value)
        elif name in self.__isupport:
            # reject any modification of __isupport
            raise AttributeError("Can't set value for %r" % name)
        elif name not in self.__dict__:
            raise AttributeError('Unknown attribute')

    def get(self, name, default=None):
        """Retrieve value for the feature ``name``.

        :param str name: feature to retrieve
        :param default: default value if the feature is not advertised
                        (defaults to ``None``)
        :return: the value for that feature, if advertised, or ``default``
        """
        return self[name] if name in self else default

    def apply(self, **kwargs):
from collections import OrderedDict
import itertools
import re
from typing import Dict, Optional, Tuple, Union

from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

Base = declarative_base()


class ISupportParameter(Base):
    """Represents a single parameter of the ISUPPORT feature.

    A parameter can be a simple flag (``True``), a value (``string`` or
    ``integer``), or a list of values (tuple of ``string`` or ``integer``).

    .. seealso::

        https://modern.ircdocs.horse/#feature-advertisement

    """
    __tablename__ = 'isupport'

    id = Column(Integer, primary_key=True)
    key = Column(String(30))
    value = Column(String(300), nullable=True)

    def __init__(self, key, value=None):
        self.key = key
        self.value = value

    @classmethod
    def from_parameter(cls, parameter):
        """Parse a parameter from an ISUPPORT message.

        :param str parameter: parameter to parse
        :return: a new parameter instance
        :rtype: :class:`ISupportParameter`

        The parameter can be:

        * a simple flag, such as ``EXCEPTS``
        * a negated flag, such as ``-EXCEPTS``
        * a parameter with a value, such as ``NICKLEN=30``
        * a parameter with a list of values, such as ``CMDS=KNOCK,MAP``
        * a parameter with a list of key-value pairs, such as
          ``PREFIX=(ov)@+``

        .. note::

            The parameter is case-insensitive, but the key in the result
            will be in uppercase.

        """
        key = parameter
        value = None

        if '=' in parameter:
            key, value = parameter.split('=', 1)

        key = key.upper()

        if value is not None:
            # try to parse the value
            if ',' in value:
                # comma-separated list
                value = tuple(value.split(','))
            elif value.startswith('(') and ')' in value:
                # list of key-value pairs
                modes, rest = value[1:].split(')', 1)
                value = tuple(zip(modes, rest))
            else:
                try:
                    # try to parse as an integer
                    value = int(value)
                except ValueError:
                    # keep as string
                    pass

        return cls(key, value)


class ISupport(dict):
    """Manage the IRC server's advertised features.

    This class handles the parsing of the ``ISUPPORT`` message (also known as
    ``005`` numeric) and provides access to the server's features.

    .. seealso::

        https://modern.ircdocs.horse/#feature-advertisement

    """
    def __init__(self, **kwargs):
        """Initialize a new instance of :class:`ISupport`.

        :param kwargs: initial parameters

        The initial parameters can be a simple flag (``True``), a value
        (``string`` or ``integer``), or a list of values (tuple of ``string``
        or ``integer``).

        .. note::

            The parameters are case-insensitive, but the keys in the result
            will be in uppercase.

        """
        self.__isupport = dict(
            (key.upper(), value)
            for key, value in kwargs.items()
        )

    def __contains__(self, key):
        """Check if a parameter is supported by the server.

        :param str key: parameter name
        :return: ``True`` if the parameter is supported, ``False`` otherwise
        :rtype: bool

        .. note::

            The parameter name is case-insensitive.

        """
        return key.upper() in self.__isupport

    def __getitem__(self, key):
        """Get the value of a parameter.

        :param str key: parameter name
        :return: the value of the parameter
        :rtype: :class:`bool`, :class:`str`, :class:`int`, or :class:`tuple`
        :raise KeyError: if the parameter is not supported

        .. note::

            The parameter name is case-insensitive.

        """
        return self.__isupport[key.upper()]

    def __iter__(self):
        """Iterate over the parameters.

        :return: an iterator over the parameters
        :rtype: iterator

        """
        return iter(self.__isupport)

    def __len__(self):
        """Get the number of parameters.

        :return: the number of parameters
        :rtype: int

        """
        return len(self.__isupport)

    def get(self, key, default=None):
        """Get the value of a parameter.

        :param str key: parameter name
        :param default: default value if the parameter is not supported
        :return: the value of the parameter, or the default value
        :rtype: :class:`bool`, :class:`str`, :class:`int`, or :class:`tuple`

        .. note::

            The parameter name is case-insensitive.

        """
        return self.__isupport.get(key.upper(), default)

    def items(self):
        """Get the parameters as a list of (key, value) pairs.

        :return: a list of (key, value) pairs
        :rtype: list

        """
        return self.__isupport.items()

    def keys(self):
        """Get the parameters as a list of keys.

        :return: a list of keys
        :rtype: list

        """
        return self.__isupport.keys()

    def values(self):
        """Get the parameters as a list of values.

        :return: a list of values
        :rtype: list

        """
        return self.__isupport.values()

    def apply(self, **kwargs):
        """Build a new instance of :class:`ISupport`.

        :return: a new instance, updated with the latest advertised features
        :rtype: :class:`ISupport`

        This method applies the latest advertised features from the server:
        the result contains the new and updated parameters, and doesn't contain
        the removed parameters (marked by ``-{PARAMNAME}``)::

            >>> updated = {'-AWAYLEN': None, 'NICKLEN': 25, 'CHANNELLEN': 10}
            >>> new = isupport.apply(**updated)
            >>> 'CHANNELLEN' in new
            True
            >>> 'AWAYLEN' in new
            False

        """
        kwargs_upper = dict(
            (key.upper(), value)
            for key, value in kwargs.items()
        )
        kept = (
            (key, value)
            for key, value in self.__isupport.items()
            if ('-%s' % key) not in kwargs_upper
        )
        updated = dict(itertools.chain(kept, kwargs_upper.items()))

        return self.__class__(**updated)

    @property
    def CHANLIMIT(self):
        """Expose ``CHANLIMIT`` as a dict, if advertised by the server.

        This exposes information about the maximum number of channels that the
        bot can join for each prefix::

            >>> isupport.CHANLIMIT
            {
                '#': 70,
                '&': None,
            }

        In that example, the bot may join 70 ``#`` channels and any number of
        ``&`` channels.

        This attribute is not available if the server does not provide the
        right information, and accessing it will raise an
        :exc:`AttributeError`.

        .. seealso::

            https://modern.ircdocs.horse/#chanlimit-parameter

        """
        if 'CHANLIMIT' not in self:
            raise AttributeError('CHANLIMIT')

        return dict(self['CHANLIMIT'])

    @property
    def CHANMODES(self):
        """Expose ``CHANMODES`` as a dict.

        This exposes information about 4 types of channel modes::

            >>> isupport.CHANMODES
            {
                'A': 'b',
                'B': 'k',
                'C': 'l',
                'D': 'imnpst',
            }

        The values are empty if the server does not provide this information.

        .. seealso::

            https://modern.ircdocs.horse/#chanmodes-parameter

        """
        if 'CHANMODES' not in self:
            return {"A": "", "B": "", "C": "", "D": ""}

        return dict(zip('ABCD', self['CHANMODES'][:4]))

    @property
    def MAXLIST(self):
        """Expose ``MAXLIST`` as a dict, if advertised by the server.

        This exposes information about maximums for combinations of modes::

            >>> isupport.MAXLIST
            {
                'beI': 100,
                'q': 50,
                'b': 50,
            }

        This attribute is not available if the server does not provide the
        right information, and accessing it will raise an
        :exc:`AttributeError`.

        .. seealso::

            https://modern.ircdocs.horse/#maxlist-parameter

        """
        if 'MAXLIST' not in self:
            raise AttributeError('MAXLIST')

        return dict(self['MAXLIST'])

    @property
    def PREFIX(self) -> Dict[str, str]:
        """Expose ``PREFIX`` as a dict, if advertised by the server.

        This exposes information about the modes and nick prefixes used for
        user privileges in channels::

            >>> isupport.PREFIX
            {
                'q': '~',
                'a': '&',
                'o': '@',
                'h': '%',
                'v': '+',
            }

        Entries are in order of descending privilege.

        This attribute is not available if the server does not provide the
        right information, and accessing it will raise an
        :exc:`AttributeError`.

        .. seealso::

            https://modern.ircdocs.horse/#prefix-parameter

        """
        if 'PREFIX' not in self:
            raise AttributeError('PREFIX')

        # This can use a normal dict once we drop python 3.6, as 3.7 promises
        # `dict` maintains insertion order. Since `OrderedDict` subclasses
        # `dict`, we'll not promise to always return the former.
        return OrderedDict(self['PREFIX'])

    @property
    def TARGMAX(self):
        """Expose ``TARGMAX`` as a dict, if advertised by the server.

        This exposes information about the maximum number of arguments for
        each command::

            >>> isupport.TARGMAX
            {
                'JOIN': None,
                'PRIVMSG': 3,
                'WHOIS': 1,
            }
            >>> isupport['TARGMAX']  # internal representation
            (('JOIN', None), ('PRIVMSG', 3), ('WHOIS', 1))

        This attribute is not available if the server does not provide the
        right information, and accessing it will raise an
        :exc:`AttributeError`.

        The internal representation of ``TARGMAX`` is a tuple of 2-value
        tuples as seen above.

        .. seealso::

            https://modern.ircdocs.horse/#targmax-parameter

        """
        if 'TARGMAX' not in self:
            raise AttributeError('TARGMAX')

        # always return a dict if None or empty tuple
        return dict(self['TARGMAX'] or [])