from abc import ABC, abstractmethod


class BaseConnector(ABC):

    @abstractmethod
    def check_connection(self):
        pass

    @abstractmethod
    def list_assets(self, *args, **kwargs):
        pass

    @abstractmethod
    def read_asset(self, *args, **kwargs):
        pass

    def upload_asset(self, *args, **kwargs):
        raise NotImplementedError

    def delete_asset(self, *args, **kwargs):
        raise NotImplementedError

    def discover_schema(self, *args, **kwargs):
        raise NotImplementedError