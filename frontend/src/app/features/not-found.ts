import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Icon } from '../shared/icon';
import { Empty } from '../shared/ui';

@Component({
  imports: [RouterLink, Icon, Empty],
  template: `<div class="card mx-auto max-w-xl">
    <app-empty
      icon="search"
      title="This page could not be found"
      text="The link may be out of date, or the brand or run it pointed at was deleted. Your portfolio has everything that still exists."
    >
      <a class="btn-primary" routerLink="/">
        <app-icon name="layers" [size]="14" /> Go to overview
      </a>
    </app-empty>
  </div>`,
})
export class NotFoundPage {}
