
import os
import yaml
import json


class SimpleConfig(dict):

    def __key(self, key):
        return "" if key is None else key.lower()

    def __str__(self):
        return json.dumps(self)

    def __setattr__(self, key, value):
        self[self.__key(key)] = value

    def __getattr__(self, key):
        return self.get(self.__key(key))

    def __getitem__(self, key):
        return super().get(self.__key(key))

    def __setitem__(self, key, value):
        return super().__setitem__(self.__key(key), value)
    

class BaseConfig(SimpleConfig):

    def __init__(self, config_file=None, **kwargs):

        if config_file:
            self.load_config_from_file(config_file)

        self.load_config_from_dict(kwargs)
        self.load_default_config()

    def load_default_config(self):
        self.output_dir = self.output_dir or "output"


    def load_config_from_file(self, config_file):
        """Load config from yaml file"""
        with open(config_file, 'r') as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        for key, value in config.items():
            self.__setattr__(key, value)

    
    def load_config_from_dict(self, dict_value):
        """Load config from dict"""
        for key, value in dict_value.items():
            self.__setattr__(key, value)

    
    def load_sub_config(self, name, file_or_dict):
        """Load sub config from file or dict"""
        if isinstance(file_or_dict, str):
            if not os.path.exists(file_or_dict):
                raise FileNotFoundError(f"File not found: {file_or_dict}")
            with open(file_or_dict, 'r') as f:
                file_or_dict = yaml.load(f, Loader=yaml.FullLoader)

        sub_config = SimpleConfig(file_or_dict)
        self.__setattr__(name, sub_config)

    
    def save_config(self, filename="config.yaml"):
        config = {}
        for key, value in self.items():
            if isinstance(value, SimpleConfig):
                items = {}
                for k, v in value.items():
                    if not k.startswith("_") and not callable(v):
                        items[k] = v
                config[key] = items

            elif not key.startswith("_") and not callable(value):
                config[key] = value

        file_path = os.path.join(self.output_dir, filename)
        with open(file_path, 'w') as f:
            yaml.dump(config, f)

        return file_path