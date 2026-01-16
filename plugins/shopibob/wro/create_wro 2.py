import os
import argparse
import json
import requests
from datetime import datetime

# NOTE: This script requires the 'requests' library.
# Please install it if you haven't already: pip install requests

# --- Configuration (from WRO_Automation_Guide.md) ---

SHIPBOB_API_BASE = "https://api.shipbob.com"

# A mapping of human-readable fulfillment center names to their ShipBob IDs, nested by region.
FULFILLMENT_CENTERS = {
    "US": {
        "US": 100,
        "Moreno Valley": 100, # Alias for clarity
        "Ontario": 156,
        "Ontario 6": 156, # Alias
        "Commerce": 111,
        "US West LTS 1": 111, # Alias
        "Fontana": 12
    },
    "AU": {
        "Sydney": 227,
        "Sydney 3": 227 # Alias
    },
    "UK": {
        "Manchester": 23
    },
    "CA": {
        "Toronto": 35
    }
}


def get_inventory_map(api_key, skus):
    """
    Fetches the inventory ID for each given SKU from the ShipBob API by querying them one by one.
    """
    print("Fetching inventory IDs for SKUs...")
    headers = {"Authorization": f"Bearer {api_key}"}
    inventory_map = {}

    for sku in skus:
        print(f"  - Fetching info for SKU: {sku}")
        # The /inventory endpoint can be queried with a single SKU.
        response = requests.get(f"{SHIPBOB_API_BASE}/2.0/inventory", headers=headers, params={'sku': sku})
        
        if response.status_code == 404:
            raise ValueError(f"SKU '{sku}' not found in ShipBob inventory.")
        response.raise_for_status()
        
        response_data = response.json()
        
        # The inventory item is inside the 'items' list in the response
        if 'items' in response_data and len(response_data['items']) > 0:
            item = response_data['items'][0]
            if 'sku' in item and 'inventory_id' in item:
                inventory_map[item['sku']] = item['inventory_id']
            else:
                raise ValueError(f"Inventory item for SKU '{sku}' is missing 'sku' or 'inventory_id' keys.")
        else:
            raise ValueError(f"No 'items' found in the API response for SKU '{sku}'.")

    print("Successfully mapped all SKUs to inventory IDs.")
    return inventory_map


def calculate_pallets(po_data, pallet_limits):
    """
    Calculates the distribution of items onto pallets based on defined limits.
    Returns a list of all pallets, with contents of each.
    """
    print("Calculating pallet distribution...")
    full_pallets = []
    remainders = []

    # 1. Create full pallets and identify remainders
    for sku, total_quantity in po_data.items():
        if sku not in pallet_limits:
            raise ValueError(f"SKU '{sku}' not found in pallet_limits definition.")
        
        limit = pallet_limits[sku]
        if limit <= 0:
            print(f"Warning: Pallet limit for SKU '{sku}' is zero or less. Skipping.")
            continue
            
        num_full_pallets = total_quantity // limit
        remainder_qty = total_quantity % limit
        
        for _ in range(num_full_pallets):
            full_pallets.append({'contents': {sku: limit}})
            
        if remainder_qty > 0:
            remainders.append({'sku': sku, 'quantity': remainder_qty})
            
    # 2. Consolidate remainders into mixed pallets
    consolidated_pallets = []
    # Group remainders by their pallet limit to ensure we don't mix items with different capacity rules
    remainders_by_limit = {}
    for rem in remainders:
        limit = pallet_limits[rem['sku']]
        if limit not in remainders_by_limit:
            remainders_by_limit[limit] = []
        remainders_by_limit[limit].append(rem)
        
    for limit, rem_group in remainders_by_limit.items():
        current_pallet_contents = {}
        current_pallet_total = 0
        
        for rem in sorted(rem_group, key=lambda x: x['quantity'], reverse=True):
            if current_pallet_total + rem['quantity'] > limit:
                if current_pallet_contents:
                    consolidated_pallets.append({'contents': current_pallet_contents})
                current_pallet_contents = {rem['sku']: rem['quantity']}
                current_pallet_total = rem['quantity']
            else:
                current_pallet_contents[rem['sku']] = current_pallet_contents.get(rem['sku'], 0) + rem['quantity']
                current_pallet_total += rem['quantity']

        if current_pallet_contents:
            consolidated_pallets.append({'contents': current_pallet_contents})
            
    all_pallets = full_pallets + consolidated_pallets
    print(f"Calculated a total of {len(all_pallets)} pallets.")
    return all_pallets


def generate_wro_boxes(pallets, po_number, inventory_map):
    """
    Generates the 'boxes' array for the WRO payload, including tracking numbers.
    """
    boxes = []
    for i, pallet in enumerate(pallets, 1):
        box_items = []
        for sku, quantity in pallet['contents'].items():
            box_items.append({
                "inventory_id": inventory_map[sku],
                "quantity": quantity
            })
        
        boxes.append({
            "tracking_number": f"{po_number}-PALLET-{i:03d}",
            "box_items": box_items
        })
    return boxes


def create_wro(api_key, po_number, arrival_date, po_data, pallet_limits, region, fulfillment_center_name):
    """
    Main function to orchestrate the WRO creation process.
    """
    try:
        # 1. Validate region and fulfillment center
        region_upper = region.upper()
        if region_upper not in FULFILLMENT_CENTERS:
            raise ValueError(f"Region '{region_upper}' is not defined. Available options: {list(FULFILLMENT_CENTERS.keys())}")
        
        if fulfillment_center_name not in FULFILLMENT_CENTERS[region_upper]:
            raise ValueError(f"Fulfillment center '{fulfillment_center_name}' not found for region '{region_upper}'. Available options: {list(FULFILLMENT_CENTERS[region_upper].keys())}")
            
        fulfillment_center_id = FULFILLMENT_CENTERS[region_upper][fulfillment_center_name]

        # 2. Get inventory IDs for all SKUs
        inventory_map = get_inventory_map(api_key, list(po_data.keys()))

        # 3. Calculate pallet configuration
        pallets = calculate_pallets(po_data, pallet_limits)

        # 4. Generate the 'boxes' part of the payload
        boxes = generate_wro_boxes(pallets, po_number, inventory_map)

        # 5. Build the final WRO payload according to the API documentation
        payload = {
            "purchase_order_number": po_number,
            "expected_arrival_date": arrival_date,
            "fulfillment_center": {
                "id": fulfillment_center_id
            },
            "boxes": boxes,
            "package_type": "Pallet",
            "box_packaging_type": "MultipleSkuPerBox"
        }

        # 6. Submit to ShipBob API
        print("Submitting WRO to ShipBob...")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        response = requests.post(f"{SHIPBOB_API_BASE}/2.0/receiving", headers=headers, data=json.dumps(payload))
        
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        result = response.json()
        print("\n✅ WRO created successfully!")
        print(f"   WRO ID: {result.get('id')}")
        print(f"   Status: {result.get('status')}")
        print(f"   Total Pallets: {len(boxes)}")
        print(f"   Fulfillment Center: {fulfillment_center_name}")

    except requests.exceptions.HTTPError as e:
        print(f"\n❌ Error creating WRO: {e.response.status_code}")
        print("   Response from ShipBob:")
        try:
            print(json.dumps(e.response.json(), indent=2))
        except json.JSONDecodeError:
            print(e.response.text)
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a ShipBob Warehouse Receiving Order (WRO).")
    
    parser.add_argument("--po-number", type=str, required=True, help="Purchase Order number (must be unique).")
    parser.add_argument("--arrival-date", type=str, required=True, help="Expected arrival date in ISO 8601 format (e.g., '2025-07-07T12:00:00Z').")
    parser.add_argument("--region", type=str, required=True, help="The destination region (e.g., 'US', 'AU', 'CA'). Determines which API key to use (SHIPBOB_API_KEY_{REGION}).")
    parser.add_argument("--fulfillment-center", type=str, required=True, help="Name of the destination fulfillment center.")
    parser.add_argument('--po-data', type=str, required=True, help='JSON string of SKU-to-quantity mapping. Example: \'{"SKU1": 100, "SKU2": 200}\'')
    parser.add_argument('--pallet-limits', type=str, required=True, help='JSON string of SKU-to-max-per-pallet mapping. Example: \'{"SKU1": 50, "SKU2": 50}\'')

    args = parser.parse_args()

    # Use region-specific API key
    region_upper = args.region.upper()
    api_key_env_var = f"SHIPBOB_API_KEY_{region_upper}"
    api_key = os.getenv(api_key_env_var)
    if not api_key:
        raise ValueError(f"{api_key_env_var} environment variable not set.")

    # Parse JSON string arguments
    try:
        po_data_dict = json.loads(args.po_data)
        pallet_limits_dict = json.loads(args.pallet_limits)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in arguments: {e}")

    create_wro(
        api_key=api_key,
        po_number=args.po_number,
        arrival_date=args.arrival_date,
        po_data=po_data_dict,
        pallet_limits=pallet_limits_dict,
        region=args.region,
        fulfillment_center_name=args.fulfillment_center
    ) 