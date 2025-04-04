from __future__ import annotations


VOICE = 1
"""Privilege level for the +v channel permission

.. versionadded:: 4.1
.. versionchanged:: 8.0
   Moved into :mod:`sopel.privileges`.
"""

HALFOP = 2
"""Privilege level for the +h channel permission

.. versionadded:: 4.1
.. versionchanged:: 8.0
   Moved into :mod:`sopel.privileges`.

.. important::

    Not all IRC networks support this privilege mode. If you are writing a
    plugin for public distribution, ensure your code behaves sensibly if only
    ``+v`` (voice) and ``+o`` (op) modes exist.

"""

OP = 4
"""Privilege level for the +o channel permission

.. versionadded:: 4.1
.. versionchanged:: 8.0
   Moved into :mod:`sopel.privileges`.
"""

ADMIN = 8
"""Privilege level for the +a channel permission

.. versionadded:: 4.1
.. versionchanged:: 8.0
   Moved into :mod:`sopel.privileges`.

.. important::

    Not all IRC networks support this privilege mode. If you are writing a
    plugin for public distribution, ensure your code behaves sensibly if only
    ``+v`` (voice) and ``+o`` (op) modes exist.

"""

OWNER = 16
"""Privilege level for the +q channel permission

.. versionadded:: 4.1
.. versionchanged:: 8.0
   Moved into :mod:`sopel.privileges`.

.. important::

    Not all IRC networks support this privilege mode. If you are writing a
    plugin for public distribution, ensure your code behaves sensibly if only
    ``+v`` (voice) and ``+o`` (op) modes exist.

"""

OPER = 32
"""Privilege level for the +y/+Y channel permissions

Note: Except for these (non-standard) channel modes, Sopel does not monitor or
store any user's OPER status.

.. versionadded:: 7.0
.. versionchanged:: 8.0
   Moved into :mod:`sopel.privileges`.

.. important::

    Not all IRC networks support this privilege mode. If you are writing a
    plugin for public distribution, ensure your code behaves sensibly if only
    ``+v`` (voice) and ``+o`` (op) modes exist.

"""