class TransactionMappings:
    """Helper class that parses transaction.json
    """

    def __init__(self, mappings):
        self.mappings = mappings

    def get_field(self, mcc, payee, field_name, default_value=None):
        field_value = None
        default = None

        mcc_group = self.mappings.get(str(mcc))

        if mcc_group:
            mapping = mcc_group.get(payee)
            if mapping and field_name in mapping:
                return mapping[field_name]
            default = mcc_group.get('default')
            if default and field_name in default:
                return default[field_name]

        return default_value
