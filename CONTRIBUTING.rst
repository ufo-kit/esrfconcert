Implementing New Features
-------------------------

New features **must** follow `PEP 8`_ and must be documented thoroughly.
Additionaly, you might want to check out `PEP 257`_ describing docstring
conventions. A good way to check your code quality are `flake8`_ and `pylint`_
tools.

Use `Sphinx`_ syntax for documentation so that we can generate
it automatically.

.. _PEP 8: http://legacy.python.org/dev/peps/pep-0008/
.. _PEP 257: http://legacy.python.org/dev/peps/pep-0257/
.. _flake8: https://pypi.python.org/pypi/flake8
.. _pylint: http://www.pylint.org
.. _Sphinx: http://sphinx-doc.org/rest.html


Reporting and Fixing Bugs
-------------------------

Any bugs concerning esrfconcert should be reported as an issue on the GitLab
`issue tracker`_.

Bug fixes and new features **must** be in a `merge request`_ form. Merge request
commits should consist of single logical changes and bear a clear message
respecting common commit message `conventions`_. Before the change is merged
it must be rebased against master.

Bug fixes must come with a unit test that will fail on the bug and pass with the
fix. If an issue exists reference it in the branch name and commit message, e.g.
``fix-92-remove-foo`` and "Fix #92: Remove foo".

.. _issue tracker: http://ankagit.anka.kit.edu/concert/esrfconcert/issues
.. _merge request: http://ankagit.anka.kit.edu/concert/esrfconcert/merge_requests
.. _conventions: http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html
