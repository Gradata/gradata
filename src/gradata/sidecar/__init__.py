"""
Gradata Sidecar — Observation Capture.
==========================================
Polls the filesystem for edits to AI-generated files and automatically
emits CORRECTION events.  No external dependencies; stdlib only.

Usage::

    from .watcher import FileWatcher

    watcher = FileWatcher("/path/to/watch", brain_db="/path/to/brain")
    watcher.track("/path/to/watch/email.html", content, output_type="email")

    # One-shot check
    change = watcher.check("/path/to/watch/email.html")

    # Blocking poll loop (Ctrl-C to stop)
    watcher.poll(interval=2.0)
"""
