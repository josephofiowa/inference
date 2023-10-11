from inference.core.cache import cache
from inference.core.managers.decorators.base import ModelManagerDecorator

lock_str = lambda z: f"locks:model-load:{z}"
class LockedLoadModelManagerDecorator(ModelManagerDecorator):
    def add_model(self, model_id: str, api_key: str):
        with cache.lock(lock_str(model_id)):
            return super().add_model(model_id, api_key)
