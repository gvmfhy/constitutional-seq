"""CLI utility functions and helpers."""

import click

# Global flag for quiet mode
_quiet_mode = False


def set_quiet_mode(quiet: bool) -> None:
    """Set the global quiet mode flag."""
    global _quiet_mode
    _quiet_mode = quiet


def echo(message: str = "", err: bool = False, **kwargs) -> None:
    """Echo wrapper that respects quiet mode."""
    if _quiet_mode and not err:
        return
    click.echo(message, err=err, **kwargs)


def secho(message: str = "", err: bool = False, **kwargs) -> None:
    """Styled echo wrapper that respects quiet mode."""
    if _quiet_mode and not err:
        return
    click.secho(message, err=err, **kwargs)


def progressbar(*args, **kwargs):
    """Progress bar wrapper that respects quiet mode."""
    if _quiet_mode:
        # Return a dummy context manager that just yields the items
        class DummyProgressBar:
            def __init__(self, items):
                self.items = items
            
            def __enter__(self):
                return self.items
            
            def __exit__(self, *args):
                pass
        
        # Extract the iterable from args or kwargs
        items = args[0] if args else kwargs.get('iterable', [])
        return DummyProgressBar(items)
    
    # In normal mode, disable label if not provided to avoid default text
    if not args and 'label' not in kwargs:
        kwargs['label'] = ''
    
    return click.progressbar(*args, **kwargs)