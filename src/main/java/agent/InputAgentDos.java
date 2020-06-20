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

import com.consts.Constants.EnumSmearing;
import com.consts.Constants.EnumSummation;
import com.consts.Constants.EnumUnitEnergy;
import com.consts.Constants.ProgramName;

public class InputAgentDos extends InputAgent{
	/**
	 * 
	 */
	private static final long serialVersionUID = -5428429337443927602L;

	public boolean setAdvanced=false;
	
	public WrapperDouble emax;
	public WrapperDouble emin;
	public WrapperDouble estep;
	public WrapperEnum energyUnit;
	
	public WrapperEnum enumSummation;
	public WrapperEnum enumSmearing;
	public WrapperDouble degauss;
	
	public InputAgentDos() {
		super(ProgramName.DOS);
		
		emax = new WrapperDouble(null);
		emin = new WrapperDouble(null);
		estep = new WrapperDouble(0.1);
		energyUnit = new WrapperEnum(EnumUnitEnergy.eV);
		
		enumSummation = new WrapperEnum(EnumSummation.from_input);
		enumSmearing = new WrapperEnum(EnumSmearing.gauss);
		degauss = new WrapperDouble(null);
	}
}
