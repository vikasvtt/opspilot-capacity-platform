import { TestBed } from '@angular/core/testing';
import { AppComponent } from './app.component';
import { ApiService } from './services/api.service';
import { AuthService } from './services/auth.service';

describe('AppComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        {provide: AuthService, useValue: {user: () => null, accessToken: () => null}},
        {provide: ApiService, useValue: {}},
      ],
    }).compileComponents();
  });

  it('shows the sign-in screen before login', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('h1').textContent).toContain('Welcome to OpsPilot');
    expect(fixture.nativeElement.querySelector('input[type="password"]')).not.toBeNull();
  });
});
