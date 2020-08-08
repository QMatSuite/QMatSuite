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
package input;

import java.util.ArrayList;

import agent.InputAgentGeo;
import agent.InputAgentNeb;
import agent.InputAgentScf;

public class NebInput extends QeInput{

	PwInput pwInput;
	
	public NebInput() {
		super("neb");
		pwInput = new PwInput();
		//probably need to manually construct things here
	}
	
	@Override
	public void loadAgent(InputAgentGeo ia1) {
		pwInput.loadAgent(ia1);
	}
	@Override
	public void loadAgent(InputAgentScf ia1) {
		pwInput.loadAgent(ia1);
	}
	public void loadAgent(ArrayList<InputAgentGeo> geoList) {
		
	}
	@Override
	public void loadAgent(InputAgentNeb ia1) {
	}
}
