from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    database_url: str
    stripe_secret_key: str = ""
    scheduler_enabled: bool = False
    default_payment_method: str = "pm_card_visa"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "billing@example.com"
    braintree_merchant_id: str = "vtwssghgp57c5z5q"
    braintree_public_key: str = "bdtw6p4m5gycnfwc"
    braintree_private_key: str = "4f027b8c22ded9877632e198ff642e72"
    braintree_merchant_account_id: str = "student"   # optional: needed for non-USD later
    anthropic_api_key: str = "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"
    anthropic_model: str = "claude-haiku-4-5-20251001"


settings = Settings()