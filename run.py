from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=not app.config["IS_PRODUCTION"])
