-- The public blueprint endpoint no longer accepts or stores email addresses.
UPDATE wallets SET email=NULL WHERE email IS NOT NULL;
