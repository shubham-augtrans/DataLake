from pymongo import MongoClient
from pymongo.errors import PyMongoError

from connectors.source.base import BaseConnector
import pandas as pd


class MongoConnector(BaseConnector):
    """
    Connector for MongoDB.
    """

    def __init__(self, datasource):
        self.datasource = datasource

        config = datasource.configuration
        print(config)
        print("datasource ",datasource.configuration)
        self.client = MongoClient(
            host=config["host"],
            port=config.get("port", 27017),
            username=config.get("username"),
            password=config.get("password"),
            authSource=config.get("authSource", "admin"),
        )

    def check_connection(self):
        """
        Test MongoDB connection.
        """
        try:
            return self.client.admin.command("ping")

        except PyMongoError as ex:
            raise Exception(f"Failed to connect to MongoDB: {str(ex)}")

    def list_databases(self):
        """
        Return all databases.
        """
        return self.client.list_database_names()

    def list_assets(self, database_name):
        """
        List all collections in a database.
        """
        db = self.client[database_name]
        return db.list_collection_names()

    def read_asset(
        self,
        database_name,
        collection_name,
        query=None,
        projection=None,
        limit=None,
    ):
        """
        Read documents from a collection into a DataFrame.
        """

        db = self.client[database_name]
        collection = db[collection_name]

        cursor = collection.find(
            query or {},
            projection,
        )

        if limit:
            cursor = cursor.limit(limit)

        documents = list(cursor)

        if not documents:
            return pd.DataFrame()

        df = pd.json_normalize(documents)

        if "_id" in df.columns:
            df["_id"] = df["_id"].astype(str)

        return df

    def insert_asset(
        self,
        database_name,
        collection_name,
        dataframe,
    ):
        """
        Insert a DataFrame into MongoDB.
        """

        db = self.client[database_name]
        collection = db[collection_name]

        records = dataframe.to_dict(orient="records")

        if records:
            collection.insert_many(records)

    def delete_asset(
        self,
        database_name,
        collection_name,
        query=None,
    ):
        """
        Delete documents from a collection.
        """

        db = self.client[database_name]
        collection = db[collection_name]

        return collection.delete_many(query or {})

    def count_asset(
        self,
        database_name,
        collection_name,
        query=None,
    ):
        """
        Count documents in a collection.
        """

        db = self.client[database_name]
        collection = db[collection_name]

        return collection.count_documents(query or {})