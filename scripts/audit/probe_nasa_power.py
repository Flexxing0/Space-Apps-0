import json

from services.providers.power import get_data

result = get_data(
    latitude=-45.86,
    longitude=-67.50,
    variable="RH2M",
    start_year=2000,
    end_year=2024
)

print("Proveedor:", result["provider"])
print("Variable:", result["name"])
print("Unidad:", result["unit"])
print("Total de registros:", len(result["series"]))

print("\nPrimeros 5 registros:")
print(json.dumps(result["series"][:5], indent=4))

print("\nÚltimos 5 registros:")
print(json.dumps(result["series"][-5:], indent=4))