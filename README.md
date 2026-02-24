# myORLEN Sensor 

This sensor is gathering gas usage data for myORLEN clients.

It uses API from https://ebok.myorlen.pl/

## Manual Configuration
Sample configuration

```yaml
sensor:
  - platform: myorlen_gas_sensor
    username: YOUR USERNAME
    password: YOUR PASSWORD
    auth_method: "ORLEN ID" # Optional. Options: ORLEN ID (default) or eBOK Login
```
It is recommended to confiure the sensor through the UI.

## Through the interface
1) Navigate to Settings > Devices & Services and then click Add Integration
2) Search for myORLEN gas sensor
3) Enter your credentials (e-mail and password)
4) Select the authentication method

## Authentication Methods

The integration supports two authentication methods:

### ORLEN ID — default
Uses the ORLEN ID (SSO) login flow. The integration initiates an OAuth-like session, navigates through the ORLEN ID login page, and retrieves an API token. This is the recommended method for accounts created or migrated to ORLEN ID.

### eBOK Login
Uses the classic eBOK direct login endpoint (`/auth/login`). Authenticates with `identificator` (e-mail) and `accessPin` (password) directly against the myORLEN eBOK API. Use this method if your account was originally created in the PGNiG/eBOK portal and has not been migrated to ORLEN ID.

## Technical Details

The sensor uses API from https://ebok.myorlen.pl 
and is particularly focused on the last reading endpoint. 

The data is refreshed every 8 hours or on the sensor startup.
The sensors are not updated if the data hasn't changed.
There are 3 different sensors created.

### Gas sensor

Currently, it reads last reading value and wear value. 
The measurement unit is volume cubic meters.

### Invoice sensor

Sensor reading last unpaid invoice.

The value of the sensor is amount to be paid in PLN. 
As a attributes the sensor is also providing due date, amount to pay, used wear and used wear in KWH.

### Cost tracking sensor

The sensor is tracking cost from the latest invoice. 
It divides amount to be paid by wear in KWH. Can be used in energy dashboard to track the cost.

### Running tests

```bash
$ pip3 install -r requirements_test.txt
```

The dependencies are installed - you can invoke `pytest` to run the tests.

```bash
$ pytest
```

# Legal notice
This is a personal project and isn't in any way affiliated with, sponsored or endorsed by myORLEN.

All product names, trademarks and registered trademarks in (the images in) this repository, are property of their respective owners. All images in this repository are used by the project for identification purposes only.

The data source for this integration is https://ebok.myorlen.pl/

The author of this project categorically rejects any and all responsibility for the data that were presented by the integration.

Anything else? Post a [question.](https://github.com/keysim86/myORLEN-Gas-Sensor/issues/new)