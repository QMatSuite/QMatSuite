/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package agent;

import com.consts.Constants.EnumOccupations;
import com.consts.Constants.EnumSmearing;
import com.consts.Constants.EnumUnitEnergy;

public class InputAgentNscf extends InputAgent{
	/**
	 * 
	 */
	private static final long serialVersionUID = 6359716753902151708L;
	public final String calcMode = "nscf";
	
	public WrapperEnum enumOccupation;//EnumOccupations 
	public WrapperEnum enumEnergyUnit;
	public WrapperDouble degauss;
	public WrapperInteger nkx,
	nky,
	nkz,
	nbnd;
	public WrapperEnum enumSmearing;//EnumSmearing
	
	public InputAgentNscf() {
		
		enumOccupation=new WrapperEnum(EnumOccupations.smearing);
		enumEnergyUnit = new WrapperEnum(EnumUnitEnergy.Ry);
		degauss = new WrapperDouble(0.02);
		nkx = new WrapperInteger(4);
		nky = new WrapperInteger(4);
		nkz = new WrapperInteger(4);
		enumSmearing=new WrapperEnum(EnumSmearing.gauss);
		nbnd = new WrapperInteger(null);
	}
}
