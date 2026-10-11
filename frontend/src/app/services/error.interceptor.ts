import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, throwError } from 'rxjs';

/** Shows a short message when the server can't be reached or a Google service fails. Pages still get the error. */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const snackBar = inject(MatSnackBar);
  return next(req).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 0) {
        snackBar.open("Can't reach the CareNest server. Check your connection and try again.", 'Dismiss', { duration: 6000 });
      } else if (err.status >= 500) {
        const detail = typeof err.error?.detail === 'string' ? err.error.detail : 'Something went wrong on our side.';
        snackBar.open(`${detail} Please try again in a moment.`, 'Dismiss', { duration: 6000 });
      }
      return throwError(() => err);
    }),
  );
};
