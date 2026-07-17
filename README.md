### Windows

Pegasus currently uses the Unix-specific function `os.uname()`, which is not available on Windows.

In `pegasus/prompts/system.py`, replace:

```python
os.uname().sysname
```

with:

```python
platform.system()
```

Then, if it is not already present, add in the line:

```python
import platform
```

This change allows Pegasus to detect the operating system correctly on Windows while maintaining compatibility with Linux and macOS.
