export interface SuccessResult<T> {
  success: true
  data: T
}

export interface FailureResult {
  success: false
  error: string
}

export type Result<T> = SuccessResult<T> | FailureResult

export function success<T>(data: T): SuccessResult<T> {
  return {
    success: true,
    data,
  }
}

export function failure(error: string): FailureResult {
  return {
    success: false,
    error,
  }
}
