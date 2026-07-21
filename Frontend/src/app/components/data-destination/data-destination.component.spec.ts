import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DataDestinationComponent } from './data-destination.component';

describe('DataDestinationComponent', () => {
  let component: DataDestinationComponent;
  let fixture: ComponentFixture<DataDestinationComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DataDestinationComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(DataDestinationComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
