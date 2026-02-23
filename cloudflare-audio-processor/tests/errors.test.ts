import { describe, it, expect } from 'vitest';
import {
  AppError,
  ValidationError,
  AuthenticationError,
  ForbiddenError,
  NotFoundError,
} from '../src/utils/errors.ts';

describe('AppError', () => {
  it('carries message, statusCode, and code', () => {
    const err = new AppError('Something broke', 500, 'INTERNAL');
    expect(err.message).toBe('Something broke');
    expect(err.statusCode).toBe(500);
    expect(err.code).toBe('INTERNAL');
    expect(err.name).toBe('AppError');
  });

  it('toJSON produces ErrorResponse format', () => {
    const err = new AppError('Bad thing', 500, 'INTERNAL');
    expect(err.toJSON()).toEqual({ error: 'Bad thing' });
  });
});

describe('ValidationError', () => {
  it('has statusCode 400 and includes details in toJSON', () => {
    const err = new ValidationError('Invalid input', 'field "name" is required');
    expect(err.statusCode).toBe(400);
    expect(err.code).toBe('VALIDATION_ERROR');
    expect(err.name).toBe('ValidationError');
    expect(err.toJSON()).toEqual({
      error: 'Invalid input',
      details: 'field "name" is required',
    });
  });

  it('omits details from toJSON when not provided', () => {
    const err = new ValidationError('Invalid input');
    expect(err.toJSON()).toEqual({ error: 'Invalid input' });
    expect(err.toJSON()).not.toHaveProperty('details');
  });
});

describe('AuthenticationError', () => {
  it('has statusCode 401 and default message', () => {
    const err = new AuthenticationError();
    expect(err.statusCode).toBe(401);
    expect(err.message).toBe('Authentication required');
    expect(err.name).toBe('AuthenticationError');
  });
});

describe('ForbiddenError', () => {
  it('has statusCode 403 and default message', () => {
    const err = new ForbiddenError();
    expect(err.statusCode).toBe(403);
    expect(err.message).toBe('Access denied');
    expect(err.name).toBe('ForbiddenError');
  });
});

describe('NotFoundError', () => {
  it('has statusCode 404 and custom message', () => {
    const err = new NotFoundError('Batch xyz not found');
    expect(err.statusCode).toBe(404);
    expect(err.message).toBe('Batch xyz not found');
    expect(err.name).toBe('NotFoundError');
    expect(err.toJSON()).toEqual({ error: 'Batch xyz not found' });
  });
});
