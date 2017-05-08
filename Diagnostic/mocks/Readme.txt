These three modules contain minimal mocks to allow the waagent code to load up on a non-Unix (e.g. windows) platform.
They're just enough to allow the import statements to be executed; if you try to actually exercise the waagent
functionality that relies upon them, you won't be happy.

In order to make these visible in the correct way, you'll need to add the full path of this directory to the
PYTHONPATH environment variable. Obviously, you shouldn't do this on Unix systems (including Linux and FreeBSD); the
real modules are visible already, and you don't need these mocks.
