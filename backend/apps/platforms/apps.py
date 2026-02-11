from django.apps import AppConfig


class PlatformsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.platforms'
    label = 'platforms'

    def ready(self):
        """
        Initialize the Connector Registry and load tool specifications on startup.
        """
        import os
        from django.conf import settings
        from connectors.registry import get_registry
        
        # Avoid running during migrations or management commands that don't need it
        if os.environ.get('RUN_MAIN') != 'true' and not os.environ.get('WERKZEUG_RUN_MAIN'):
            # This check helps avoid double loading in auto-reload mode, 
            # though get_registry() is a singleton so it's safe.
            pass

        try:
            registry = get_registry()
            base_dir = settings.BASE_DIR
            tool_specs_dir = os.path.join(base_dir, 'tool_specs')
            
            if os.path.exists(tool_specs_dir):
                # Load generic/shared tools if any
                registry.load_tool_specs(tool_specs_dir)
                
                # Load platform-specific tools
                for item in os.listdir(tool_specs_dir):
                    item_path = os.path.join(tool_specs_dir, item)
                    if os.path.isdir(item_path):
                        registry.load_tool_specs(item_path, platform=item)
            else:
                pass
                # logging.warning(f"Tool specs directory not found: {tool_specs_dir}")
                
        except Exception as e:
            # Don't crash startup if tool loading fails, but log it
            import logging
            logging.getLogger(__name__).error(f"Failed to load tool specs: {e}")

