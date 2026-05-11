from fastapi import FastAPI

def create_app():
    app = FastAPI(__name__)
    
    # Load configuration from environment variables or config file
    app.config.from_mapping(
        SECRET_KEY='your_secret_key',
        # Add other configuration variables here
    )

    # Register blueprints for routes
    from .routes import main as main_routes
    app.register_blueprint(main_routes)

    return app