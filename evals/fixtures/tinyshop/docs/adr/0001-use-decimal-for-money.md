# 1. Use Decimal for money

Status: accepted

We store all amounts as `decimal.Decimal` and round half up to cents only at the end, to avoid float rounding errors in totals.
