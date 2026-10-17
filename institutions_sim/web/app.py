from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import dash
import dash_bootstrap_components as dbc
from .layout import create_layout
from .callbacks import register_callbacks


def create_app(debug: bool = False) -> dash.Dash:
    app = dash.Dash(
        __name__,
        assets_folder=str(Path(__file__).parent / "assets"),
        title="institutions-sim",
        suppress_callback_exceptions=True,
        meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    )
    app.layout = create_layout()
    register_callbacks(app)
    return app


def main() -> None:
    app = create_app(debug=True)
    app.run(debug=True, host="0.0.0.0", port=8050)


if __name__ == "__main__":
    main()
