import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { IntakeForm } from '../components/IntakeForm';

describe('IntakeForm Component', () => {
  it('renders intake form with default fields', () => {
    render(<IntakeForm onSubmit={vi.fn()} isLoading={false} />);
    expect(screen.getByLabelText(/Customer Identifier/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Customer Complaint/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Submit & Execute Case/i })).toBeInTheDocument();
  });

  it('validates customer ID cannot be blank', () => {
    const mockSubmit = vi.fn();
    render(<IntakeForm onSubmit={mockSubmit} isLoading={false} />);

    const idInput = screen.getByLabelText(/Customer Identifier/i);
    fireEvent.change(idInput, { target: { value: '   ' } });

    const submitBtn = screen.getByRole('button', { name: /Submit & Execute Case/i });
    fireEvent.click(submitBtn);

    expect(screen.getByText(/Customer identifier is required/i)).toBeInTheDocument();
    expect(mockSubmit).not.toHaveBeenCalled();
  });

  it('validates illegal characters in customer ID', () => {
    const mockSubmit = vi.fn();
    render(<IntakeForm onSubmit={mockSubmit} isLoading={false} />);

    const idInput = screen.getByLabelText(/Customer Identifier/i);
    fireEvent.change(idInput, { target: { value: 'bad!id@#$' } });

    const submitBtn = screen.getByRole('button', { name: /Submit & Execute Case/i });
    fireEvent.click(submitBtn);

    expect(screen.getByText(/only letters, numbers, hyphens, or underscores/i)).toBeInTheDocument();
    expect(mockSubmit).not.toHaveBeenCalled();
  });

  it('validates complaint message cannot be blank', () => {
    const mockSubmit = vi.fn();
    render(<IntakeForm onSubmit={mockSubmit} isLoading={false} />);

    const msgInput = screen.getByLabelText(/Customer Complaint/i);
    fireEvent.change(msgInput, { target: { value: '   ' } });

    const submitBtn = screen.getByRole('button', { name: /Submit & Execute Case/i });
    fireEvent.click(submitBtn);

    expect(screen.getByText(/Customer complaint text cannot be empty/i)).toBeInTheDocument();
    expect(mockSubmit).not.toHaveBeenCalled();
  });

  it('submits valid payload in live integration mode by default and switches demo profile', () => {
    const mockSubmit = vi.fn();
    render(<IntakeForm onSubmit={mockSubmit} isLoading={false} />);

    // Click demo customer profile chip
    const chip = screen.getByRole('button', { name: /Jordan Lee/i });
    fireEvent.click(chip);

    const submitBtn = screen.getByRole('button', { name: /Submit & Execute Case/i });
    fireEvent.click(submitBtn);

    expect(mockSubmit).toHaveBeenCalledTimes(1);
    expect(mockSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        customer_id: 'cust-demo-002',
        channel: 'web',
        mock: false,
        scenario: 'delivery_delay',
      })
    );
  });

  it('submits mock: true when mock mode is enabled via the toggle', () => {
    const mockSubmit = vi.fn();
    render(<IntakeForm onSubmit={mockSubmit} isLoading={false} />);

    const toggle = screen.getByRole('checkbox', { name: /Toggle integration mode/i });
    fireEvent.click(toggle);

    const submitBtn = screen.getByRole('button', { name: /Submit & Execute Case/i });
    fireEvent.click(submitBtn);

    expect(mockSubmit).toHaveBeenCalledTimes(1);
    expect(mockSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        mock: true,
      })
    );
  });
});
