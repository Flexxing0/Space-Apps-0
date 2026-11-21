def normalize_data(raw_series, fill_value=-999):

    normalized = []     

    for date, value in sorted(raw_series.items()):

        year = date[:4]
        month = date[4:]

        # Excluir registros que no sean meses reales
        if month not in [f"{i:02d}" for i in range(1, 13)]:
            continue

        # Identificar datos faltantes
        if value == fill_value:
            value = None

        normalized.append({
            "date": f"{year}-{month}",
            "value": value
        })

    return normalized