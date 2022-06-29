import requests


def get_all_products(token):
    headers = {
        'Authorization': f'Bearer {token}',
    }
    response = requests.get(
        'https://api.moltin.com/v2/products',
        headers=headers,
    )
    response.raise_for_status()
    return response.json()['data']


def get_product(token, product_id):
    headers = {
        'Authorization': f'Bearer {token}',
    }
    response = requests.get(
        f'https://api.moltin.com/v2/products/{product_id}',
        headers=headers,
    )
    response.raise_for_status()
    return response.json()['data']


def get_image_url(token, image_id):
    headers = {
        'Authorization': f'Bearer {token}',
    }
    response = requests.get(
        f'https://api.moltin.com/v2/files/{image_id}',
        headers=headers,
    )
    response.raise_for_status()
    return response.json()['data']['link']['href']


def add_product_to_cart(token, cart_id, product_id, quantity):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    json_data = {
        'data': {
            'id': product_id,
            'type': 'cart_item',
            'quantity': quantity,
        },
    }

    response = requests.post(
        f'https://api.moltin.com/v2/carts/{cart_id}/items',
        headers=headers,
        json=json_data,
    )
    response.raise_for_status()


def delete_cart_item(token, cart_id, product_id):
    headers = {
        'Authorization': f'Bearer {token}',
    }
    response = requests.delete(
        f'https://api.moltin.com/v2/carts/{cart_id}/items/{product_id}',
        headers=headers,
    )
    response.raise_for_status()


def get_cart(token, cart_id):
    headers = {
        'Authorization': f'Bearer {token}',
    }
    response = requests.get(
        f'https://api.moltin.com/v2/carts/{cart_id}/items',
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def create_customer(token, name, email):
    headers = {
        'Authorization': f'Bearer {token}',
    }
    json_data = {
        'data': {
            'type': 'customer',
            'name': name,
            'email': email,
        },
    }
    response = requests.post(
        'https://api.moltin.com/v2/customers',
        headers=headers,
        json=json_data,
    )
    response.raise_for_status()


def create_moltin_token(client_id, client_secret):
    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials',
    }
    response = requests.post(
        'https://api.moltin.com/oauth/access_token',
        data=data,
    )
    response.raise_for_status()
    token = response.json()
    return token['access_token'], token['expires_in']
