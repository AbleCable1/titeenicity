##Interaktiivinen verkkopeli vuoden 2019 Titeenien taistoille


###Asennus paikalliseen ympäristöön:

- Verkkopeli käyttää AWS:n DynamoDB:tä ja SES:iä, joten AWS SDK tulee olla asennettuna ja konfiguroituna. https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html
- Lisäksi tulee luoda seuraavat DynamoDB-taulut:
  - Table name: titeeni-player, Primary key: "key" (tyyppiä string)
  - Table name: titeeni-usedqrcode, Primary key: "qrcode_key" (tyyppiä string)
- Myös AWS SES tulee olla konfiguroituna käytettävällä AWS-tilillä
- Lisäksi seuraavat titeeni.py-tiedostosta löytyvät vakiot tulee asettaa käytetyn ympäristön mukaisesti.
  - BASE_URL: haluttu domain, esim. http://localhost:5000/ (kauttamerkki lopussa on oleellinen)
  - AWS_EMAIL_SENDER_ADDRESS: Sähköpostiosoite, jota voidaan käyttää viestien lähettämiseen SES:illä
  - AWS_SES_REGION: Haluttu aws region, jossa sähköpostipalvelin sijaitsee
  - AWS_DYNAMODB_REGION: Haluttu aws region, jossa kätettävät DynamoDb-taulut sijaisevat
  - CAPTCHA_SECRET_KEY: Recaptcha API:n salainen avain
  - CAPTCHA_PUBLIC_KEY: Recaptcha API:n julkinen avain
  - Älä vahingossakaan committaa näitä repoon. Repossa käytetään vain placeholder-arvoja. 