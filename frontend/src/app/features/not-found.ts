import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Empty } from '../shared/ui';
@Component({
  imports: [RouterLink, Empty],
  template: `<app-empty
    title="This page could not be found"
    text="Return to your portfolio to find your brands and analyses."
    ><a class="btn primary" routerLink="/">Go to overview</a></app-empty
  >`,
})
export class NotFoundPage {}
