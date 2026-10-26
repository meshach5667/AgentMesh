import { groupSecret } from '../MfaSetup';

it('groups the authenticator key in fours for typing', () => {
  expect(groupSecret('JBSWY3DPEHPK3PXPJBSWY3DP')).toBe('JBSW Y3DP EHPK 3PXP JBSW Y3DP');
  expect(groupSecret('ABCDEF')).toBe('ABCD EF');
});
