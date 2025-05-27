def format_number(phone):
    """
    Formats the phone number by removing spaces/dashes and ensuring +52 country code.
    Leading zeros are removed.
    """
    phone = str(phone).replace(" ", "").replace("-", "")
    if not phone.startswith("+52"):
        phone = "+52" + phone.lstrip("0")
    return phone
