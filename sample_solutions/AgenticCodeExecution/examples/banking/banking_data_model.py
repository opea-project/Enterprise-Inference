"""Data models for the banking card-management domain."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


CardStatus = Literal["active", "frozen", "blocked"]
CardType = Literal["debit", "credit"]
BlockReason = Literal["lost", "stolen", "suspected_fraud", "customer_request"]


class CustomerName(BaseModel):
	"""Customer full name."""

	first_name: str = Field(description="First name")
	last_name: str = Field(description="Last name")


class CustomerAddress(BaseModel):
	"""Customer mailing address."""

	address1: str = Field(description="First line of the address")
	address2: str = Field(description="Second line of the address")
	city: str = Field(description="City")
	state: str = Field(description="State")
	country: str = Field(description="Country")
	zip: str = Field(description="ZIP / postal code")


class CardLimits(BaseModel):
	"""Daily card control limits."""

	atm_withdrawal_limit: int = Field(description="Daily ATM withdrawal limit in USD")
	pos_purchase_limit: int = Field(description="Daily in-person purchase limit in USD")
	ecommerce_purchase_limit: int = Field(description="Daily e-commerce purchase limit in USD")
	contactless_purchase_limit: int = Field(description="Daily contactless purchase limit in USD")


class CardLimitBounds(BaseModel):
	"""Allowed minimum and maximum values for each adjustable limit."""

	minimum: CardLimits = Field(description="Minimum allowed values")
	maximum: CardLimits = Field(description="Maximum allowed values")


class CardEvent(BaseModel):
	"""Audit record for a card state change."""

	timestamp: str = Field(description="Event timestamp in ISO-8601 UTC format")
	action: str = Field(description="Action that occurred")
	details: Dict[str, Any] = Field(description="Structured details for the action")


class Card(BaseModel):
	"""Bank card record with controls and state."""

	card_id: str = Field(description="Unique card identifier")
	customer_id: str = Field(description="Owning customer identifier")
	nickname: str = Field(description="Customer-visible nickname for the card")
	product_name: str = Field(description="Card product name")
	card_type: CardType = Field(description="Card type")
	network: str = Field(description="Card network, such as Visa or Mastercard")
	linked_account: str = Field(description="Linked deposit or credit account identifier")
	last_four: str = Field(description="Last four digits of the card")
	expiry_month: int = Field(description="Expiry month")
	expiry_year: int = Field(description="Expiry year")
	status: CardStatus = Field(description="Current card status")
	limits: CardLimits = Field(description="Current active card limits")
	limit_bounds: CardLimitBounds = Field(description="Allowed min/max limit values")
	temporary_block_reason: Optional[str] = Field(
		default=None,
		description="Temporary freeze reason, if the card is frozen",
	)
	block_reason: Optional[BlockReason] = Field(
		default=None,
		description="Permanent block reason, if the card is blocked",
	)
	events: List[CardEvent] = Field(
		default_factory=list,
		description="Audit history for this card",
	)


class Customer(BaseModel):
	"""Bank customer profile."""

	customer_id: str = Field(description="Unique customer identifier")
	name: CustomerName = Field(description="Customer name")
	email: str = Field(description="Customer email address")
	date_of_birth: str = Field(description="Date of birth in YYYY-MM-DD format")
	phone_last_four: str = Field(description="Last four digits of the registered phone number")
	address: CustomerAddress = Field(description="Primary mailing address")
	cards: List[str] = Field(description="List of card ids owned by the customer")


class BankingDB(BaseModel):
	"""Database containing banking card-management data."""

	model_config = {"extra": "allow"}

	customers: Dict[str, Customer] = Field(
		description="Dictionary of customers indexed by customer id"
	)
	cards: Dict[str, Card] = Field(
		description="Dictionary of cards indexed by card id"
	)
	meta: Dict[str, Any] = Field(
		default_factory=dict,
		description="Database metadata",
	)

	_db_path: str = ""

	@classmethod
	def load(cls, path: str | Path) -> "BankingDB":
		"""Load the database from a JSON file."""
		with open(path, "r") as f:
			data = json.load(f)
		db = cls.model_validate(data)
		db._db_path = str(path)
		return db

	def save(self) -> None:
		"""Save the database back to the JSON file."""
		if self._db_path:
			with open(self._db_path, "w") as f:
				json.dump(self.model_dump(exclude={"_db_path"}), f, indent=2)
			print(f"Database saved to {self._db_path}")

	def get_statistics(self) -> Dict[str, Any]:
		"""Get a summary of the database contents."""
		return {
			"num_customers": len(self.customers),
			"num_cards": len(self.cards),
			"num_blocked_cards": sum(1 for card in self.cards.values() if card.status == "blocked"),
			"num_frozen_cards": sum(1 for card in self.cards.values() if card.status == "frozen"),
		}
