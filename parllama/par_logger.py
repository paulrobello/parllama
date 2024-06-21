"""Parllama logger."""

import inspect

from textual import Logger, LoggerError, active_app, constants


class ParLogger(Logger):
    """Parllama logger."""

    def __call__(self, *args: object, **kwargs) -> None:
        if constants.LOG_FILE:
            output = " ".join(str(arg) for arg in args)
            if kwargs:
                key_values = " ".join(
                    f"{key}={value!r}" for key, value in kwargs.items()
                )
                output = f"{output} {key_values}" if output else key_values

            with open(constants.LOG_FILE, "a", encoding="utf-8") as log_file:
                print(output, file=log_file)
        try:
            app = active_app.get()
        except LookupError:
            print_args = (*args, *[f"{key}={value!r}" for key, value in kwargs.items()])
            print(*print_args)
            return
        # if app.devtools is None or not app.devtools.is_connected:
        #     return

        current_frame = inspect.currentframe()
        assert current_frame is not None
        previous_frame = current_frame.f_back
        assert previous_frame is not None
        caller = inspect.getframeinfo(previous_frame)

        _log = self._log or app._log
        try:
            _log(
                self._group,
                self._verbosity,
                caller,
                *args,
                **kwargs,
            )
        except LoggerError:
            # If there is not active app, try printing
            print_args = (*args, *[f"{key}={value!r}" for key, value in kwargs.items()])
            print(*print_args)
