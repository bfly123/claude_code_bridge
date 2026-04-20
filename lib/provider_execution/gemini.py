import sys

from provider_backends.gemini import execution as _backend_module

sys.modules[__name__] = _backend_module
