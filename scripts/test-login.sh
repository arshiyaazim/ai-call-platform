#!/bin/bash
curl -s -w "\nHTTP_CODE:%{http_code}\n" -X POST http://127.0.0.1:8101/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"azim@iamazim.com","password":"ChangeMe123!"}'
