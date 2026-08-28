import os
import yaml

class KPIContract:
    def __init__(self, data):
        self.name = data['name']
        self.definition = data['definition']
        self.calculation = data['calculation']
        self.source_table = data['source_table']
        self.grain = data['grain']
        self.calendar = data['calendar']
        self.refresh_cadence = data['refresh_cadence']
        self.known_drivers = data.get('known_drivers', [])
        self.materiality_threshold = data.get('materiality_threshold', {})
        self.lineage = data.get('lineage', {})
        self.access_restrictions = data.get('access_restrictions', {})

class ContractRegistry:
    def __init__(self, contracts_dir="contracts"):
        self.contracts = {}
        self.contracts_dir = contracts_dir
        self.load_contracts()

    def load_contracts(self):
        if not os.path.exists(self.contracts_dir):
            # Try to resolve relative path if run from subdirectory
            self.contracts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "contracts")
            
        if not os.path.exists(self.contracts_dir):
            raise FileNotFoundError(f"Contracts directory not found: {self.contracts_dir}")
            
        for file in os.listdir(self.contracts_dir):
            if file.endswith(".yaml") or file.endswith(".yml"):
                filepath = os.path.join(self.contracts_dir, file)
                with open(filepath, "r") as f:
                    try:
                        data = yaml.safe_load(f)
                        contract = KPIContract(data)
                        self.contracts[contract.name] = contract
                    except Exception as e:
                        print(f"Error loading contract from {file}: {e}")

    def get(self, name):
        """Retrieve a contract by name."""
        return self.contracts.get(name)

    def list_kpis(self):
        """Get a list of all loaded KPI names."""
        return list(self.contracts.keys())

# Shared registry instance
registry = ContractRegistry()

if __name__ == "__main__":
    # Quick sanity check
    print("Loaded KPIs in registry:", registry.list_kpis())
    rev = registry.get("revenue")
    if rev:
        print(f"Revenue Grain: {rev.grain}, Source: {rev.source_table}")
