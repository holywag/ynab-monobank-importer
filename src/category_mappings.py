from collections import namedtuple

class CategoryMappings:
    Category = namedtuple("Category", "group name")

    def __init__(self, mappings):
        self.mappings = mappings

    def get_category(self, mcc, payee_name):
        category_group_name = None
        category_name = None
        default = None

        mcc_group = self.mappings.get(str(mcc))

        if mcc_group:
            default = mcc_group['default']
            mapping = mcc_group.get(payee_name)
            if mapping:
                category_group_name = mapping.get('category_group')
                category_name = mapping.get('category_name')

        if not category_group_name:
            category_group_name = default and default.get('category_group')
        if category_group_name and not category_name:
            category_name = default and default.get('category_name')

        return (category_group_name and category_name) and \
            self.Category(group=category_group_name, name=category_name)

    def get_payee(self, mcc, payee_name):
        payee = None
        default = None

        mcc_group = self.mappings.get(str(mcc))

        if mcc_group:
            default = mcc_group['default']
            mapping = mcc_group.get(payee_name)
            if mapping:
                payee = mapping.get('payee')
        
        if not payee_name:
            payee = default and default.get('payee_name')

        return payee or (default and default.get('payee_name'))
