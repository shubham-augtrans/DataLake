def __init__(self, datasource):
    self.datasource = datasource

    config = datasource.configuration
    print("Mongo config:", config)