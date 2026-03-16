from __future__ import annotations
import importlib.util
import logging
import os

from enum import StrEnum
from typing import Any, Callable


class ImportSupportException(StrEnum):
    no_entry_point = "No Entry Point Error"
    extension_failed = "Extension Failed"
    extension_not_found = "Extension Not Found"


class ImportSupporter:
    def __init__(
        self,
        *default_argument,
        setup_func: Callable[[object, str | int], Any] = None,
        logger_name: str = "core.import_supporter",
        is_debug: bool = False,
        **default_key_argument,
    ):
        self.setup_func = setup_func or self.default_setup_func
        self.logger = logging.getLogger(logger_name)
        self.is_debug = is_debug

        self.default_argument = default_argument
        self.default_key_argument = default_key_argument

    @staticmethod
    def logging_error(
        code: ImportSupportException, name: str | int = None, description: str = None
    ) -> str:
        if name is not None:
            if description is not None:
                return f"{code.value}: {name} ({description})"
            return f"{code.value}: {name}"
        return code.value

    def default_setup_func(self, library: object, name: str | int) -> Any:
        if not hasattr(library, "setup"):
            self.logger.error(
                self.logging_error(ImportSupportException.no_entry_point, name)
            )
            return

        setup = getattr(library, "setup")
        try:
            response = setup(*self.default_argument, **self.default_key_argument)
        except Exception as error:
            error_log = self._get_error_log(error)
            self.logger.error(
                self.logging_error(
                    ImportSupportException.extension_failed, name, error_log
                )
            )
            if self.is_debug:
                raise error
            return
        return response

    @staticmethod
    def _get_error_log(error):
        exc_arg_list = [str(x) for x in error.args]
        if not exc_arg_list:
            error_log = error.__class__.__name__
        else:
            error_log = error.__class__.__name__ + ": " + ", ".join(exc_arg_list)
        return error_log

    @staticmethod
    def _find_spec(name: str):
        return importlib.util.find_spec(name)

    def _get_spec(self, spec, name: str | int):
        lib = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(lib)  # type: ignore
        except Exception as error:
            error_log = self._get_error_log(error)
            self.logger.error(
                self.logging_error(
                    ImportSupportException.extension_not_found, name, error_log
                )
            )
            if self.is_debug:
                raise error
            return

        return lib

    def load_module(self, name: str):
        spec = self._find_spec(name)
        if spec is None:
            self.logger.error(
                self.logging_error(ImportSupportException.extension_not_found, name)
            )
            return

        lib = self._get_spec(spec, name)
        if lib is None:
            return

        return self.setup_func(lib, name)

    def load_modules(
        self, package, directory, after_loaded: Callable[..., None] = None
    ):
        package_path = package.replace(".", os.sep)
        packages = [
            package + "." + file[:-3]
            for file in os.listdir(os.path.join(directory, package_path))
            if file.endswith(".py")
        ]
        responses = []
        for package in packages:
            response = self.load_module(package)
            responses.append(response)

        if after_loaded is not None:
            after_loaded()
        return responses
