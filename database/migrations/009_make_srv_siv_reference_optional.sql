-- Migration 009: Make SIV reference optional on Store Return Vouchers (SRV)
-- Implements ADR-012 (APPROVED): drops chk_srv_reference so SRVs may be posted
-- either linked to a prior posted SIV or as direct/unlinked warehouse returns.

BEGIN;

ALTER TABLE public.transactions DROP CONSTRAINT IF EXISTS chk_srv_reference;

COMMIT;
