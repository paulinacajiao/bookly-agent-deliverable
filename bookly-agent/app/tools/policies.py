"""
Business policy constants - the AOP (Agent Operating Procedure) made explicit.

These are the numbers the deterministic guards enforce. Keeping them here (not
buried in prompt text, not hard-coded inside functions) means:
  * a human can audit the rules in one place,
  * changing the return window is a one-line edit, not a prompt rewrite,
  * the MODEL never gets to decide them - the code does.

This file is the boundary between "what the business decided" and "what the
agent is allowed to do."
"""

# How long after delivery a customer may request a return.
RETURN_WINDOW_DAYS = 30

# Order statuses from which a return is even possible.
RETURNABLE_STATUSES = {"delivered"}
