"""
Application Factory
====================
Creates and configures the Flask application using the factory pattern.
This allows multiple app instances (useful for testing) and keeps
initialization logic in one place.
"""

import os
from flask import Flask

from config import config


def create_app(config_name=None):
    """
    Create and configure the Flask application.

    Args:
        config_name: Configuration to use ('development', 'production').
                     Defaults to FLASK_CONFIG env var or 'default'.

    Returns:
        Configured Flask application instance.
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')

    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static',
    )

    # Load configuration
    app.config.from_object(config[config_name])

    # Ensure default placeholder folder structure and branding folders exist
    ensure_placeholder_image(app)
    ensure_branding_dir(app)

    # Initialize CSVDataLoader on startup
    from app.data_loader import CSVDataLoader
    data_dir = os.path.abspath(os.path.join(app.root_path, '../data'))
    app.data_loader = CSVDataLoader(data_dir)

    # Register context processor to inject default fallback image URL
    @app.context_processor
    def inject_defaults():
        from flask import url_for
        from app.routes import COUNTRY_FLAGS
        default_img = app.config.get('DEFAULT_PLAYER_IMAGE', 'players/default.png')
        default_url = url_for('static', filename='img/' + default_img)
        default_frame = app.config.get('DEFAULT_FRAME_IMAGE', 'teams/default_frame.png')
        default_frame_url = url_for('static', filename='img/' + default_frame)

        # Check for custom branding logo and favicon
        static_folder = app.static_folder
        if not os.path.isabs(static_folder):
            static_folder = os.path.abspath(os.path.join(app.root_path, static_folder))
        branding_dir = os.path.normpath(os.path.join(static_folder, 'img', 'branding'))

        logo_url = None
        for logo_name in ['logo.png', 'logo.svg', 'logo.jpg', 'logo.webp']:
            if os.path.isfile(os.path.join(branding_dir, logo_name)):
                logo_url = url_for('static', filename=f'img/branding/{logo_name}')
                break

        favicon_url = None
        for fav_name in ['favicon.ico', 'favicon.png', 'favicon.svg']:
            if os.path.isfile(os.path.join(branding_dir, fav_name)):
                favicon_url = url_for('static', filename=f'img/branding/{fav_name}')
                break

        return {
            'default_player_image_url': default_url,
            'default_frame_image_url': default_frame_url,
            'flags': COUNTRY_FLAGS,
            'logo_url': logo_url,
            'favicon_url': favicon_url,
        }

    # Register Jinja2 global function for flag images
    from markupsafe import Markup

    def flag_img(country_code, size=24):
        """
        Generate an inline <img> tag for a country flag using flagcdn.com SVG CDN.
        Returns empty string if no valid country code is provided.
        """
        if not country_code:
            return ''
        src = f'https://flagcdn.com/{country_code}.svg'
        return Markup(
            f'<img src="{src}" alt="" '
            f'width="{size}" height="{int(size * 0.75)}" '
            f'style="display:inline-block;vertical-align:middle;border-radius:2px;" '
            f'loading="lazy">'
        )

    app.jinja_env.globals['flag_img'] = flag_img

    # Register blueprints / routes
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    return app


def ensure_placeholder_image(app):
    """
    Ensures that the folder for the placeholder image exists,
    and copies the default fallback image if not present.
    """
    import shutil
    placeholder_rel_path = app.config.get('DEFAULT_PLAYER_IMAGE', 'players/default.png')
    
    static_folder = app.static_folder
    if not os.path.isabs(static_folder):
        static_folder = os.path.abspath(os.path.join(app.root_path, static_folder))
        
    placeholder_abs_path = os.path.normpath(os.path.join(static_folder, 'img', placeholder_rel_path))
    
    # Create directory structure if not exist
    placeholder_dir = os.path.dirname(placeholder_abs_path)
    if not os.path.exists(placeholder_dir):
        os.makedirs(placeholder_dir, exist_ok=True)
        
    # Copy fallback or write tiny empty image
    if not os.path.isfile(placeholder_abs_path):
        source_fallback = os.path.normpath(os.path.join(static_folder, 'img', 'default.png'))
        if os.path.isfile(source_fallback):
            shutil.copy2(source_fallback, placeholder_abs_path)
        else:
            tiny_png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc` \x05\x00\x00\x0b\x00\x01\x02\x1f\x14\x8b\x00\x00\x00\x00IEND\xaeB`\x82'
            with open(placeholder_abs_path, 'wb') as f:
                f.write(tiny_png_bytes)


def ensure_branding_dir(app):
    """
    Ensures that the static/img/branding folder exists for logo and favicon images.
    """
    static_folder = app.static_folder
    if not os.path.isabs(static_folder):
        static_folder = os.path.abspath(os.path.join(app.root_path, static_folder))
    branding_dir = os.path.normpath(os.path.join(static_folder, 'img', 'branding'))
    if not os.path.exists(branding_dir):
        os.makedirs(branding_dir, exist_ok=True)


