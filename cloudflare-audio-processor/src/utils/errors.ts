/**
 * Custom error classes with HTTP status codes for structured API responses.
 *
 * All errors produce an ErrorResponse-shaped JSON via toJSON().
 */

import type { ErrorResponse } from '../types/api.ts';

/** Base application error with HTTP status code and machine-readable code. */
export class AppError extends Error {
  readonly statusCode: number;
  readonly code: string;

  constructor(message: string, statusCode: number, code: string) {
    super(message);
    this.name = 'AppError';
    this.statusCode = statusCode;
    this.code = code;
  }

  /** Produces an ErrorResponse-compatible JSON object for API responses. */
  toJSON(): ErrorResponse {
    return { error: this.message };
  }
}

/** 400 Bad Request -- invalid input or failed validation. */
export class ValidationError extends AppError {
  readonly details?: string;

  constructor(message: string, details?: string) {
    super(message, 400, 'VALIDATION_ERROR');
    this.name = 'ValidationError';
    this.details = details;
  }

  toJSON(): ErrorResponse {
    return {
      error: this.message,
      ...(this.details ? { details: this.details } : {}),
    };
  }
}

/** 401 Unauthorized -- missing or invalid authentication. */
export class AuthenticationError extends AppError {
  constructor(message = 'Authentication required') {
    super(message, 401, 'AUTHENTICATION_ERROR');
    this.name = 'AuthenticationError';
  }
}

/** 403 Forbidden -- authenticated but lacks permission. */
export class ForbiddenError extends AppError {
  constructor(message = 'Access denied') {
    super(message, 403, 'FORBIDDEN');
    this.name = 'ForbiddenError';
  }
}

/** 404 Not Found -- resource does not exist. */
export class NotFoundError extends AppError {
  constructor(message = 'Resource not found') {
    super(message, 404, 'NOT_FOUND');
    this.name = 'NotFoundError';
  }
}

/** 413 Payload Too Large -- request body exceeds size limit. */
export class PayloadTooLargeError extends AppError {
  constructor(message = 'Payload too large') {
    super(message, 413, 'PAYLOAD_TOO_LARGE');
    this.name = 'PayloadTooLargeError';
  }
}

/** 500 Internal Server Error -- storage or infrastructure failure. */
export class StorageError extends AppError {
  constructor(message = 'Storage operation failed') {
    super(message, 500, 'STORAGE_ERROR');
    this.name = 'StorageError';
  }
}
