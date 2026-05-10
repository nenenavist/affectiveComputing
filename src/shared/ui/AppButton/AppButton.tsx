import { Button, ButtonProps } from '@mui/material';

export type AppButtonProps = ButtonProps;

export const AppButton = ({ variant = 'contained', size = 'large', ...props }: AppButtonProps) => {
  return <Button disableElevation variant={variant} size={size} {...props} />;
};
