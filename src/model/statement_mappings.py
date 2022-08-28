from collections import namedtuple

StatementMapping = namedtuple('StatementMapping', 'payee category_group category_name transfer_account')

class StatementMappings:
    """Helper class that parses statement.json
    """

    def __init__(self, mappings):
        self.mappings = mappings

    def __get_field(mapping, default, field_name, default_value=None):
        return mapping.get(field_name, default.get(field_name, default_value))

    def get(self, mcc, payee):
        mcc_group = self.mappings.get(str(mcc))

        mapping = mcc_group and mcc_group.get(payee) or {}
        default = mcc_group and mcc_group.get('default') or {}

        return StatementMapping(
            payee=StatementMappings.__get_field(mapping, default, 'payee', payee),
            category_group=StatementMappings.__get_field(mapping, default, 'category_group'),
            category_name=StatementMappings.__get_field(mapping, default, 'category_name'),
            transfer_account=StatementMappings.__get_field(mapping, default, 'transfer_account'))
