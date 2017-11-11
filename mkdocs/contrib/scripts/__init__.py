import importlib
import logging
from pathlib import Path

from mkdocs import utils
from mkdocs.config import config_options
from mkdocs.plugins import BasePlugin, EVENTS


log = logging.getLogger('mkdocs.plugins.scripts')


OPTIONS_SCHEMA = (
    ('module', config_options.File(exists=True, required=True)),
    ('function', config_options.Type(utils.string_types, default='main')),
    ('process_object', config_options.Type(bool, default=False)),
    ('pass_parameters', config_options.Type(list, default=())),
    ('extra_parameters', config_options.Type(dict, default={}))
)


class ScriptPluginMeta(type):
    def __new__(mcs, name, bases, namespace):
        config_scheme = []
        for event in EVENTS:
            config_scheme.append(
                (event,
                 config_options.ConfigItems(*OPTIONS_SCHEMA, required=False))
            )
            if f'on_{event}' not in namespace:
                namespace[f'on_{event}'] = mcs.method_factory(event)

        namespace['config_scheme'] = tuple(config_scheme)

        return super().__new__(mcs, name, bases, namespace)

    @staticmethod
    def method_factory(event_name):
        def event_method(self, obj, **kwargs):
            return self._run_scripts(event_name, obj, kwargs)
        return event_method


class ScriptsPlugin(BasePlugin, metaclass=ScriptPluginMeta):
    def __init__(self):
        self._base_dir = None

    def _load_module(self, module_path, ):
        if not module_path.endswith('.py'):
            module_path += '.py'

        module_name = 'script_plugin_' + module_path[:-3]
        module_name = module_name.replace('/', '.').replace('-', '_')

        module_path = (self._base_dir / module_path).resolve()
        module_spec = importlib.util.spec_from_file_location(module_name,
                                                             module_path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        return module

    def _run_scripts(self, event, obj, kwargs):
        for script_config in self.config[event]:
            module_name = script_config['module']
            module = self._load_module(module_name)
            function_name = script_config['function']
            parameters = {k: v for k, v in kwargs.items()
                          if k in script_config['pass_parameters']}
            parameters.update(script_config['extra_parameters'])
            function = vars(module)[function_name]

            log.debug(f"Executing '{function_name}' from '{module_name}' "
                      f'with parameters: {parameters}.')
            if script_config['process_object']:
                obj = function(obj, **parameters)
            else:
                function(**parameters)
        return obj

    def on_config(self, config, **kwargs):
        self._base_dir = Path(config['config_file_path']).parent
        return self._run_scripts('config', config, kwargs)


__all__ = [ScriptsPlugin.__name__]
