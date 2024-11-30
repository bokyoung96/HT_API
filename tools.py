import json


class Tools:
    def __init__(self):
        pass

    @staticmethod
    def load_config(file_path: str):
        try:
            with open(file_path, 'r') as file:
                config = json.load(file)
                return config
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found at {file_path}.")
        except json.JSONDecodeError:
            raise ValueError("Config file is not a valid JSON format.")
