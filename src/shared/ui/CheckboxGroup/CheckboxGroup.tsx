import { Checkbox, FormControlLabel, FormGroup } from '@mui/material';

export type CheckboxOption = {
  id: string;
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
};

type CheckboxGroupProps = {
  options: CheckboxOption[];
};

export const CheckboxGroup = ({ options }: CheckboxGroupProps) => {
  return (
    <FormGroup>
      {options.map((option) => (
        <FormControlLabel
          key={option.id}
          control={
            <Checkbox
              checked={option.checked}
              onChange={(event) => option.onChange(event.target.checked)}
            />
          }
          label={option.label}
        />
      ))}
    </FormGroup>
  );
};
