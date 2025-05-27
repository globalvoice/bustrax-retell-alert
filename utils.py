def format_number(phone):
    # Ensure country code +52 for Mexico
    phone = str(phone).replace(" ", "").replace("-", "")
    if not phone.startswith("+52"):
        phone = "+52" + phone.lstrip("0")
    return phone
