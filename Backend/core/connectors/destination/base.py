from abc import ABC, abstractmethod


class BaseDestinationConnector(ABC):
    """
    Base class for all destination connectors.
    """

    @abstractmethod
    def check_connection(self):
        """
        Test the connection.
        """
        pass

    @abstractmethod
    def write_dataframe(self, dataframe, table_name):
        """
        Write a Pandas DataFrame to the destination.

        - PostgreSQL -> SQL table
        - MinIO -> Parquet file
        """
        pass

    @abstractmethod
    def insert_rows(self, table_name, rows):
        """
        Insert a list of rows into the destination.

        For file-based destinations like MinIO, this can internally
        convert rows to a DataFrame and call write_dataframe().
        """
        pass

    def execute(self, query, params=None):
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support execute()."
        )

    def fetch_all(self, query, params=None):
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support fetch_all()."
        )

    def close(self):
        pass