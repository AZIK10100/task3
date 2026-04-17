users = []


def save_user(message):
    global users
    phone_number = message.contact.phone_number
    name = message.contact.full_name
    user_id = message.from_user.id
    users.append({"user_id": user_id, "phone_number": phone_number, name: name})
