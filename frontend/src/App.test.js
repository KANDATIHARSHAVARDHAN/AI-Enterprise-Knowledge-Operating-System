import { render } from '@testing-library/react';
import App from './App';

jest.mock('react-router-dom', () => ({
  BrowserRouter: ({ children }) => <div>{children}</div>,
  Routes: ({ children }) => <div>{children}</div>,
  Route: ({ element }) => element,
  Navigate: () => null,
}));

test('renders the application without crashing', () => {
  const { container } = render(<App />);
  expect(container).toBeInTheDocument();
});
